import re

with open(r'e:\osmanli\lua_src\worldDispatchArmyView.lua', 'rb') as f:
    content = f.read()

# Let's search for patterns around GOLD, FOOD, WOOD, IRON, MITHRIL
matches = re.findall(b'(?:FOOD|WOOD|IRON|MITHRIL|GOLD|SILVER|RESOURCE|resourceType)[^\x00]{1,100}', content)
for m in matches[:30]:
    print(m)
