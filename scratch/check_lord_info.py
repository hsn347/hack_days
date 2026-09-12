import json

with open(r"e:\osmanli\dumps\fahed.K140_at_gmail.com_login_init.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print(json.dumps(d.get("lordInfoCtrl", {}), indent=2))
print("cityCtrl:", json.dumps(d.get("cityCtrl", {}), indent=2))
