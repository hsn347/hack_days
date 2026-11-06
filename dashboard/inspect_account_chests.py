# -*- coding: utf-8 -*-
import sys, os
_ROOT = r"e:\osmanli"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
with open(os.path.join(_ROOT, "inspect_account_chests.py"), "r", encoding="utf-8") as f:
    code = f.read()
exec(compile(code, "inspect_account_chests.py", "exec"))
