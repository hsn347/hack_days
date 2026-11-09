import os
import re
import ast
import glob

tasks_dir = r"e:\osmanli\tasks"
root_files = [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"]

task_files = glob.glob(os.path.join(tasks_dir, "*.py"))
all_files = task_files + root_files

# Regex for init_data access:
# conn.init_data.get('...') or init_data['...'] or init_data.get('...')
init_data_patterns = [
    r"init_data(?:\.get\(|\[)['\"]([a-zA-Z0-9_]+)['\"]",
    r"init(?:\.get\(|\[)['\"]([a-zA-Z0-9_]+)['\"]",
    r"['\"]([a-zA-Z0-9_]+Ctrl|[a-zA-Z0-9_]+AgCtrl)['\"]",
]

# Command patterns:
# send_command(cmd, sub, ...), call(cmd, sub, ...), _send_command(...)
cmd_patterns = [
    r"send_command\(\s*(\d+)\s*,\s*(\d+)",
    r"call\(\s*(\d+)\s*,\s*(\d+)",
    r"_send_command\(\s*(\d+)\s*,\s*(\d+)",
    r"cmd_id\s*=\s*(\d+).*?sub_id\s*=\s*(\d+)",
    r"send_packet\(\s*(\d+)\s*,\s*(\d+)",
]

controller_usage = {}
command_usage = {}

for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        lines = content.splitlines()

    # Search init_data access
    for idx, line in enumerate(lines, 1):
        # find init_data['xxx'] or init_data.get('xxx')
        m_list = re.findall(r"init_data\s*(?:\.get\(|\[\s*)\s*['\"]([a-zA-Z0-9_]+)['\"]", line)
        for m in m_list:
            controller_usage.setdefault(m, []).append((fname, idx, line.strip()))
        
        # also check if "xxxCtrl" in init_data or "xxxAgCtrl"
        m_ctrl = re.findall(r"['\"]([a-zA-Z0-9_]+(?:Ctrl|AgCtrl))['\"]", line)
        for c in m_ctrl:
            if c not in [x[0] for x in m_list]:
                # check context
                if "init_data" in line or "conn" in line or "data" in line:
                    controller_usage.setdefault(c, []).append((fname, idx, line.strip()))

        # Search commands
        for pat in cmd_patterns:
            for m in re.finditer(pat, line):
                cmd_pair = f"{m.group(1)}/{m.group(2)}"
                command_usage.setdefault(cmd_pair, []).append((fname, idx, line.strip()))

print("=== CONTROLLERS FOUND ===")
for ctrl in sorted(controller_usage.keys()):
    files = sorted(list(set(x[0] for x in controller_usage[ctrl])))
    print(f"{ctrl} ({len(controller_usage[ctrl])} occurrences across {len(files)} files: {', '.join(files[:5])})")

print("\n=== COMMANDS FOUND ===")
for cmd in sorted(command_usage.keys()):
    files = sorted(list(set(x[0] for x in command_usage[cmd])))
    print(f"{cmd} ({len(command_usage[cmd])} occurrences in {', '.join(files[:3])})")
