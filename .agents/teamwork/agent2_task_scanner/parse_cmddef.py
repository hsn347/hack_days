import re

cmd_defs = {}

with open(r"e:\osmanli\game file\lua_src\cmdDef_dec.lua", "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        # e.g. cmdDef.CMD_CITY = 1001 or similar
        m = re.search(r"cmdDef\.([A-Za-z0-9_]+)\s*=\s*['\"]?(\d+)['\"]?", line)
        if m:
            cmd_defs[m.group(2)] = m.group(1)
        m2 = re.search(r"([A-Za-z0-9_]+)\s*=\s*\{\s*cmd\s*=\s*['\"]?(\d+)['\"]?", line)
        if m2:
            cmd_defs[m2.group(2)] = m2.group(1)

print(f"Found {len(cmd_defs)} command definitions in cmdDef_dec.lua:")
for cmd in sorted(cmd_defs.keys(), key=lambda x: int(x) if x.isdigit() else 99999):
    print(f"  CMD {cmd:5} -> {cmd_defs[cmd]}")
