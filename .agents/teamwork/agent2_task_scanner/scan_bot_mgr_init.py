with open(r"e:\osmanli\bot_manager.py", "r", encoding="utf-8", errors="ignore") as f:
    for lno, line in enumerate(f, 1):
        if "init_data" in line:
            print(f"{lno:4}: {line.strip()}")
