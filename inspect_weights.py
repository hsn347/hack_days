import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scratch_armyinfo.lua', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# Let's find each [number] = { ... } at top level
pattern = re.compile(r'\[(\d+)\]\s*=\s*\{', re.MULTILINE)
matches = list(pattern.finditer(text))

units = []
for i in range(len(matches)):
    start = matches[i].start()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    block = text[start:end]
    
    aid = re.search(r'armyID\s*=\s*(\d+)', block)
    bid = re.search(r'barrackID\s*=\s*(\d+)', block)
    blv = re.search(r'barrackLevel\s*=\s*(\d+)', block)
    fw = re.search(r'freeWeight\s*=\s*([0-9.]+)', block)
    atype = re.search(r'armyType\s*=\s*(\d+)', block)
    
    if aid:
        units.append({
            'id': int(aid.group(1)),
            'bid': int(bid.group(1)) if bid else 0,
            'blv': int(blv.group(1)) if blv else 0,
            'fw': float(fw.group(1)) if fw else 0.0,
            'type': int(atype.group(1)) if atype else 0
        })

print(f"Total units parsed: {len(units)}")
for u in sorted(units, key=lambda x: x['id']):
    print(f"ID: {u['id']:<8} Barrack: {u['bid']:<4} Type: {u['type']:<2} Lv: {u['blv']:<4} FreeWeight: {u['fw']}")
