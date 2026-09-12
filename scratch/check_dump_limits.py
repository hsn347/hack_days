import json

with open(r"e:\osmanli\dumps\fahed.K140_at_gmail.com_login_init.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for k, v in d.items():
    s = json.dumps(v)
    if "march" in s.lower() or "limi" in s.lower() or "soldier" in s.lower() or "maxarmy" in s.lower():
        print(f"Key: {k}, type={type(v)}")

# Also let's check duelCompileArmy or formations:
print("--- heroFormationAgCtrl ---")
print(d.get("heroFormationAgCtrl", {}))
