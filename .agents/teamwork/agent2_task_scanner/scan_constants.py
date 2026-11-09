import os
import re
import glob

task_files = glob.glob(r"e:\osmanli\tasks\*.py") + [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"]

const_patterns = [
    re.compile(r"([A-Z0-9_]*CMD[A-Z0-9_]*)\s*=\s*['\"]?(\d+)['\"]?"),
    re.compile(r"([A-Z0-9_]*REQ[A-Z0-9_]*)\s*=\s*['\"]?(\d+)['\"]?"),
    re.compile(r"([A-Z0-9_]*SUB[A-Z0-9_]*)\s*=\s*['\"]?(\d+)['\"]?"),
    re.compile(r"([A-Z0-9_]*OP[A-Z0-9_]*)\s*=\s*['\"]?(\d+)['\"]?"),
]

var_query_pattern = re.compile(r"\b(?:query|send_nowait)\(\s*([^,\)]+)\s*,\s*([^,\)]+)")

file_constants = {}
dynamic_queries = []

for fpath in task_files:
    fname = os.path.basename(fpath)
    constants = {}
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        
    for lno, line in enumerate(lines, 1):
        for pat in const_patterns:
            for m in pat.finditer(line):
                constants[m.group(1)] = m.group(2)
                
        # check query calls
        for m in var_query_pattern.finditer(line):
            arg1 = m.group(1).strip()
            arg2 = m.group(2).strip()
            # if not plain string digits
            if not (re.match(r"^['\"]?\d+['\"]?$", arg1) and re.match(r"^['\"]?\d+['\"]?$", arg2)):
                dynamic_queries.append((fname, lno, arg1, arg2, line.strip()))
                
    file_constants[fname] = constants

print("=== DYNAMIC / CONSTANT QUERY CALLS ===")
for fname, lno, arg1, arg2, line in dynamic_queries:
    # try to resolve
    c1 = file_constants.get(fname, {}).get(arg1.replace("self.", "").replace("cls.", ""), arg1)
    c2 = file_constants.get(fname, {}).get(arg2.replace("self.", "").replace("cls.", ""), arg2)
    print(f"{fname}:{lno} -> ({arg1}, {arg2}) => resolved: ({c1}, {c2}) | {line[:60]}")
