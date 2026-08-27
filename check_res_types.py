import re

with open(r'e:\osmanli\Attack_ copy.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Check what was captured in previous runs
print('Checking previous captured resources:')
res_types = {}
for m in re.findall(r'(\d+-\d+-5-(\d+)-\d+)', text):
    res_types[m[1]] = res_types.get(m[1], 0) + 1
print(res_types)
