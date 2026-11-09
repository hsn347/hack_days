with open(r"e:\osmanli\game file\lua_src\src\src\app\module\city\cityCtrl.lua", "r", encoding="utf-8", errors="ignore") as f:
    for lno, line in enumerate(f, 1):
        if any(w in line for w in ["cmdDef", "sendCmd", "sendMsg", "gNotifyID", "register", "initData", "blist", "reslist", "openChargeQueue"]):
            if any(k in line for k in ["function", "cmdDef", "gNotifyID"]):
                print(f"{lno:4}: {line.strip()[:100]}")
