import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scratch_armydescribe.lua', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# search language files for text translations
# let's find strings in lang or i18n
import glob
lang_files = glob.glob('**/*ar*.lua', recursive=True) + glob.glob('**/*lang*.lua', recursive=True) + glob.glob('**/*string*.lua', recursive=True)
print("Lang files:", lang_files[:5])

# Also let's check speciality for 701-712
pattern = re.compile(r'\[(7\d\d)\]\s*=\s*\{([^}]+)\}', re.MULTILINE)
for m in pattern.finditer(text):
    aid = m.group(1)
    block = m.group(2)
    name = re.search(r'armyName\s*=\s*"([^"]+)"', block)
    spec = re.search(r'speciality\s*=\s*\{([^}]+)\}', block)
    print(f"ID: {aid}, NameKey: {name.group(1) if name else ''}, Speciality: {spec.group(1).replace('\n', '').strip() if spec else ''}")
