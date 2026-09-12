import json, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open(r"e:\osmanli\dumps\fahed.K140_at_gmail.com_login_init.json", "r", encoding="utf-8") as f:
    d = json.load(f)

lic = d.get("lordInfoCtrl", {})
for k in sorted(lic.keys()):
    print(f"{k}: {lic[k]}")
