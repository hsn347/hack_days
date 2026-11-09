import os
import re
import glob
import ast

all_files = sorted(glob.glob(r"e:\osmanli\tasks\*.py") + [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"])

query_pattern = re.compile(r"(?:conn\.query|self\.query|conn\.send_nowait|self\.send_nowait)\s*\(\s*([^,\)]+)\s*,\s*([^,\)]+)(?:,\s*([^,\)]+))?")

results = []

for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        
    # collect constants in this file
    const_map = {}
    for line in lines:
        m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*['\"]?(\d+)['\"]?", line)
        if m:
            const_map[m.group(1)] = m.group(2)
        m_cls = re.match(r"^\s*(?:self|cls)\.([A-Za-z0-9_]+)\s*=\s*['\"]?(\d+)['\"]?", line)
        if m_cls:
            const_map[m_cls.group(1)] = m_cls.group(2)

    for lno, line in enumerate(lines, 1):
        if "query(" in line or "send_nowait(" in line:
            if "def query" in line or "def send_nowait" in line or "tasks   =" in line:
                continue
            
            # extract arguments
            # Sometimes the call is multi-line, let's grab next 3 lines
            full_call = "".join(lines[lno-1:min(len(lines), lno+5)])
            m = re.search(r"(?:query|send_nowait)\s*\(\s*([^\n,]+)\s*,\s*([^\n,]+)(?:,\s*([^\n\)]+))?", full_call)
            if m:
                c1 = m.group(1).strip().strip("'\"")
                c2 = m.group(2).strip().strip("'\"")
                payload = m.group(3).strip() if m.group(3) else "{}"
                
                # resolve c1 and c2 if variable
                c1_clean = c1.replace("self.", "").replace("cls.", "")
                c2_clean = c2.replace("self.", "").replace("cls.", "")
                
                c1_resolved = const_map.get(c1_clean, c1)
                c2_resolved = const_map.get(c2_clean, c2)
                
                # look for comments on the line or preceding line
                comment = ""
                if "#" in line:
                    comment = line.split("#", 1)[1].strip()
                elif lno > 1 and "#" in lines[lno-2]:
                    comment = lines[lno-2].split("#", 1)[1].strip()
                    
                results.append({
                    "file": fname,
                    "line": lno,
                    "cmd": c1_resolved,
                    "subcmd": c2_resolved,
                    "raw_args": (c1, c2),
                    "payload_preview": payload[:40],
                    "comment": comment
                })

print(f"Mapped {len(results)} query calls.")
# Print distinct command pairs
cmd_pairs = {}
for r in results:
    pair = f"{r['cmd']}/{r['subcmd']}"
    cmd_pairs.setdefault(pair, []).append(r)

print(f"Distinct Command Pairs: {len(cmd_pairs)}")
for pair in sorted(cmd_pairs.keys()):
    files = sorted(list(set(x["file"] for x in cmd_pairs[pair])))
    print(f"  {pair:12} : {len(cmd_pairs[pair]):2} calls across {len(files)} files ({', '.join(files[:3])})")
