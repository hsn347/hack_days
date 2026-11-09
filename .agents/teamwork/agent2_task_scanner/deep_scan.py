import os
import re
import ast
import json
import glob

tasks_dir = r"e:\osmanli\tasks"
task_files = sorted(glob.glob(os.path.join(tasks_dir, "*.py")))
all_files = task_files + [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"]

# Data structures to aggregate
# 1. Controller access: ctrl_name -> list of (file, line_num, code_snippet, context_type)
controllers_found = {}

# 2. Commands called: (cmd, subcmd) -> list of (file, line_num, code_snippet)
commands_found = {}

# 3. Task info: task_file -> {name, controllers, commands}
tasks_info = {}

# Patterns for init_data access
re_init_get = re.compile(r"(?:init_data|init)\.get\(\s*['\"]([a-zA-Z0-9_]+)['\"]")
re_init_sub = re.compile(r"(?:init_data|init)\[\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\]")
re_init_in  = re.compile(r"['\"]([a-zA-Z0-9_]+)['\"]\s+in\s+(?:self\.)?(?:conn\.)?(?:init_data|init)")
re_conn_init = re.compile(r"conn\.init_data\.(?:get\(|\[\s*)['\"]([a-zA-Z0-9_]+)['\"]")
re_ctrl_literal = re.compile(r"['\"]([a-zA-Z0-9_]+(?:Ctrl|AgCtrl|Mgr))['\"]")
re_check_and_merge = re.compile(r"check_and_merge_controller\(\s*['\"]([a-zA-Z0-9_]+)['\"]")

# Patterns for commands
# query('1001', '1', ...) or query("1001", "1") or query(1001, 1) or send_nowait(...)
re_query = re.compile(r"\b(?:query|send_nowait|_send_command|pack_request)\(\s*['\"]?(\d+)['\"]?\s*,\s*['\"]?(\d+)['\"]?")
# also look for tuple like ('1001', '1') or ("1001", "1")
re_cmd_tuple = re.compile(r"['\"](\d{4})['\"]\s*,\s*['\"](\d{1,4})['\"]")

for fpath in all_files:
    fname = os.path.basename(fpath)
    tinfo = {
        "controllers": set(),
        "commands": set(),
        "lines_count": 0
    }
    
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    tinfo["lines_count"] = len(lines)
    
    for lno, line in enumerate(lines, 1):
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#"):
            continue
            
        # Check init_data accesses
        for pat in [re_init_get, re_init_sub, re_init_in, re_conn_init, re_check_and_merge]:
            for match in pat.finditer(line):
                ctrl = match.group(1)
                controllers_found.setdefault(ctrl, []).append((fname, lno, clean_line))
                tinfo["controllers"].add(ctrl)
                
        # Also check general Ctrl literals if they look like controller references
        for match in re_ctrl_literal.finditer(line):
            ctrl = match.group(1)
            # Filter out non-controllers
            if any(term in line for term in ["init_data", "conn", "controller", "retdata", "data", "check_and_merge"]):
                controllers_found.setdefault(ctrl, []).append((fname, lno, clean_line))
                tinfo["controllers"].add(ctrl)

        # Check commands
        for pat in [re_query]:
            for match in pat.finditer(line):
                cmd_pair = f"{match.group(1)}/{match.group(2)}"
                commands_found.setdefault(cmd_pair, []).append((fname, lno, clean_line))
                tinfo["commands"].add(cmd_pair)
                
    tasks_info[fname] = tinfo

output_data = {
    "controllers": {k: len(v) for k, v in controllers_found.items()},
    "commands": {k: len(v) for k, v in commands_found.items()},
    "tasks_summary": {k: {"controllers": list(v["controllers"]), "commands": list(v["commands"])} for k, v in tasks_info.items()}
}

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\scan_results.json", "w", encoding="utf-8") as out:
    json.dump(output_data, out, indent=2)

print(f"Total Unique Controllers Identified: {len(controllers_found)}")
print(f"Total Unique Commands Identified: {len(commands_found)}")
print(f"Scanned {len(all_files)} files.")
