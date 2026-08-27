import re

with open(r'e:\osmanli\lua_src\worldDispatchArmyView.lua', 'rb') as f:
    content = f.read()

strings = re.findall(b'[\x20-\x7E]{4,}', content)
for s in strings:
    if any(k in s.lower() for k in [b'bautohero', b'recommend', b'autoselect', b'recommendation', b'targettype', b'expeditiontype']):
        print(s.decode('latin1'))
