import re

with open(r'e:\osmanli\lua_src\worldDispatchArmyView.lua', 'rb') as f:
    content = f.read()

# Extract all ASCII / readable strings
strings = re.findall(b'[\x20-\x7E]{3,}', content)
decoded = [s.decode('latin1') for s in strings]

print("=== Strings in worldDispatchArmyView ===")
for s in decoded:
    if any(k in s.lower() for k in ['mapobjtype', 'maptype', 'relic', 'ruin', 'judian', 'bandit', 'boss', 'tory', 'battery', 'stronghold']):
        print(s)
