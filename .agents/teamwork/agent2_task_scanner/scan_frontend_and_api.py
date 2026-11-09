import os
import re
import glob

search_dirs = [
    r"e:\osmanli\api_server.py",
    r"e:\osmanli\core\*.py",
    r"e:\osmanli\dashboard\src\**\*.ts",
    r"e:\osmanli\dashboard\src\**\*.tsx",
]

files = []
for p in search_dirs:
    files.extend(glob.glob(p, recursive=True))

ctrl_pattern = re.compile(r"['\"]([a-zA-Z0-9_]+(?:Ctrl|AgCtrl|Mgr))['\"]")
init_pattern = re.compile(r"init_data(?:\.get\(|\[)['\"]([a-zA-Z0-9_]+)['\"]")

found_in_api = set()

for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        for lno, line in enumerate(f, 1):
            for m in ctrl_pattern.finditer(line):
                found_in_api.add((m.group(1), fname, lno))
            for m in init_pattern.finditer(line):
                found_in_api.add((m.group(1), fname, lno))

print(f"Scanned {len(files)} files in api_server, core, and dashboard.")
api_ctrls = sorted(list(set(x[0] for x in found_in_api)))
print(f"Found {len(api_ctrls)} controllers mentioned:")
for c in api_ctrls:
    mentions = [f"{fname}:{lno}" for ctrl, fname, lno in found_in_api if ctrl == c]
    print(f"  {c} -> {', '.join(mentions[:3])}")
