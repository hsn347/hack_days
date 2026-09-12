import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = r"e:\osmanli\game file\lua_src\cmdDef_dec.lua"
with open(path, "rb") as f:
    text = f.read().decode("utf-16", errors="replace")

for line in text.splitlines():
    if "QUEUE" in line or "1007" in line or "MASS" in line:
        print(line)
