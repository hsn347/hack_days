import json

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\tasks_detailed_audit.json", "r", encoding="utf-8") as f:
    audit = json.load(f)

print("=== TASKS WITH NO IDENTIFIED CONTROLLERS ===")
no_ctrls = [f for f, data in audit.items() if not data["controllers"]]
for f in no_ctrls:
    print(f"- {f} (cmds: {audit[f]['commands']})")

print("\n=== TASKS AND THEIR CONTROLLERS (ALL 54) ===")
for f, data in sorted(audit.items()):
    ctrls_str = ", ".join(data["controllers"]) if data["controllers"] else "None (stateless/standalone)"
    cmds_str = ", ".join(data["commands"]) if data["commands"] else "None"
    print(f"{f:25} -> ctrls: [{ctrls_str}] | cmds: [{cmds_str}]")

print("\n=== ELF DECOUPLING AUDIT (GEMINI.md Rule 7) ===")
for f, data in audit.items():
    if data["elf_check"]["has_elf"]:
        print(f"File {f}: mentions elf: {data['elf_check']['has_elf']}, mentions march_manager: {data['elf_check']['has_march_mgr']}")
