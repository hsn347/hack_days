import json

path = r"e:\osmanli\dumps\fahed.K140_at_gmail.com_login_init.json"
with open(path, "r", encoding="utf-8") as f:
    d = json.load(f)

# check gErrDef or notices if any in dumps
print("Check done")
