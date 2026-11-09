import re
import json

gcmd = {}
current_cmd_name = ""
current_cmd_val = ""

with open(r"e:\osmanli\game file\lua_src\cmdDef_dec.lua", "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        # CMD_... = "1001"
        m_cmd = re.search(r"CMD_([A-Za-z0-9_]+)\s*=\s*['\"](\d+)['\"]", line)
        if m_cmd:
            current_cmd_name = m_cmd.group(1)
            current_cmd_val = m_cmd.group(2)
            gcmd.setdefault(current_cmd_val, {"name": current_cmd_name, "reqs": {}})
            continue
            
        m_req = re.search(r"REQ_([A-Za-z0-9_]+)\s*=\s*['\"](\d+)['\"]", line)
        if m_req and current_cmd_val:
            gcmd[current_cmd_val]["reqs"][m_req.group(2)] = m_req.group(1)

print(f"Parsed {len(gcmd)} CMD modules from cmdDef_dec.lua")

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\gcmd_parsed.json", "w", encoding="utf-8") as out:
    json.dump(gcmd, out, indent=2)

for c, data in sorted(gcmd.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 9999):
    print(f"CMD {c:5}: {data['name']} ({len(data['reqs'])} subcommands)")
