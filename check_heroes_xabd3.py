import json, sys
sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open(r'C:/Users/Computer Home/.gemini/antigravity-ide/brain/801b092d-99bc-4b80-bea3-7bd0e962e35e/scratch/x_abd3_dump.json', 'r', encoding='utf-8'))

heroes = d.get('heroCtrl', [])
print(f'Total heroes in x_abd3: {len(heroes)}')
for i, h in enumerate(heroes):
    hid = h.get('id')
    hlv = h.get('lv')
    skills = h.get('skillList', {})
    s_list = []
    if isinstance(skills, dict):
        for sk, sv in skills.items():
            if isinstance(sv, dict):
                s_list.append(f"{sv.get('id')}:lv{sv.get('lv')}")
    print(f"Hero {hid} (Lv {hlv}): skills = {s_list}")
