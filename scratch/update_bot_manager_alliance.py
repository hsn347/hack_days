# -*- coding: utf-8 -*-
path = r"e:\osmanli\bot_manager.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = '        "gold_donations": 0,         # عدد تبرعات الذهب (0 = مجاني فقط بدون ذهب إطلاقاً لمنع استهلاك الذهب)'
addition = '\n        "open_treasure": True,       # استلام وفتح كنز التحالف'

if "\r\n" in text:
    addition = addition.replace("\n", "\r\n")

if target in text:
    new_text = text.replace(target, target + addition, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("SUCCESS")
else:
    print("TARGET_NOT_FOUND")

