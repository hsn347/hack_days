import os
import re
import glob

all_files = glob.glob(r"e:\osmanli\tasks\*.py") + [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"]

all_query_calls = []

for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        for lno, line in enumerate(f, 1):
            if "query(" in line or "send_nowait(" in line:
                if not ("def query" in line or "def send_nowait" in line):
                    all_query_calls.append((fname, lno, line.strip()))

print(f"Total query/send_nowait call-sites: {len(all_query_calls)}")
